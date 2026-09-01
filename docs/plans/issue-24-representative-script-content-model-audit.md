# Issue 24 plan — representative-script content-model audit

## Objective

Produce the private-evidence-grounded, public-safe investigation required by
GitHub issue #24. The deliverables must account for every material structural
and semantic family observed in the representative production script, map each
family to the product specification and canonical `ScriptDocument` model, make
or assign the required design decisions, supply a sanitized prototype brief,
and state the exact bounded impact on issue #13's Claude instructions.

## Scope

1. Inspect the representative Google Doc read-only and retain only structural
   counts and generalized classifications.
2. Reconcile the observed vocabulary against:
   - `docs/Script-to-Timeline Product Spec - Fable Rev2.md`;
   - the frozen `contracts/script-document-v1.schema.json` boundary;
   - the accepted ScriptDocument validator decisions; and
   - issue #13's proposed VERA suite design contract and Claude brief.
3. Record one coverage status for every observed family: `Covered`, `Design
   decision required`, `Intentionally excluded`, or `Missing`.
4. Resolve or assign explicit follow-ups for variants and section-linked
   parked material; hierarchical right-column roles; unplaced/three-point
   timing; Sequences, Option sets, and Comparison stacks; comments/mentions;
   `Propose cut`; image acquisition; capture timing/retention; motion presets;
   one-action YouTube watch-page composites; OCR-derived capture Spotlight
   mattes and Resolve handoff; typed visible prompter annotations; graphics
   provenance; and non-durable asset references.
5. Create a fictional, sanitized prototype input brief that exercises every
   accepted content family without reproducing the private script.
6. State the exact additions issue #13 must make before its Claude brief can be
   accepted.

## Exclusions

- Do not publish, copy, attach, quote, or identify the private production
  script or its URL.
- Do not edit the source Google Doc, its permissions, its sharing, or any
  connected project data.
- Do not change contracts, generated types, fixtures, golden files, accepted
  tests, application code, dependencies, parsing/import behavior, media
  ingestion, asset upload, graphics behavior, deployments, or permissions.
- Do not build the high-fidelity prototype or redesign Research Video Clips.
- Do not decide, reconcile, or wire visual tokens; issue #21 remains
  independent.
- Do not create follow-up roadmap issues before the Producer accepts that the
  corresponding gap is real.

## Evidence and privacy controls

- The source is read-only private evidence.
- Repository artifacts may contain only aggregate counts, generalized content
  families, fictional examples, and public product-contract references.
- No source title, document identifier, URL, production name, distinctive
  quotation, participant, claim, or source-specific link may enter the
  repository or a public GitHub comment.
- Structural counts are reproducible from the native Google Docs resource but
  the raw response is not retained in the repository.

## Contracts, fixtures, and dependencies

- Touched contracts: none.
- Touched fixtures or golden files: none.
- Touched application code: none.
- New dependencies: none.
- Roadmap dependencies: `None`, as recorded on issue #24.
- Related dependency impact: issue #13 is blocked by #24 and may return to
  review only after the Producer accepts #24 and the bounded handoff is applied.

## Deliverables

- `docs/investigations/issue-24-representative-script-coverage.md`
- `docs/prototypes/issue-24-sanitized-prototype-input-brief.md`

## Automated checks

1. Run `git diff --check` and inspect the complete diff for private evidence.
2. Search the added files for the private document identifier and URL shape;
   both must be absent.
3. Run the repository's pinned `npm run validate` gate.
4. Confirm contracts, fixtures, generated types, accepted tests, dependency
   manifests, lockfiles, and application code are unchanged.
5. Reinspect issue #24 and move it only to `In review` with sanitized evidence.

## Producer acceptance outline

The final handoff will tell the Producer exactly which two artifacts to open,
in what order, what result to expect for the structural inventory, coverage
map, decision record, sanitized fixture, and issue #13 delta, and the precise
acceptance or failure response to record. Issue #24 remains `In review` until
that response is explicit.
