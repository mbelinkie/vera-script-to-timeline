# Issue 105 plan — evaluate and pin the local Spotlight OCR engine

## Objective

Compare two locally runnable OCR candidates on one retained synthetic webpage
corpus, select one exact engine/model/profile for Spotlight, and hand issue #41
an implementation-ready adapter and provenance decision without implementing
that adapter.

## Authority and dependency

- GitHub issue #105 and the VERA roadmap are the live scope, routing,
  ownership, and acceptance authority. At claim time the issue was `Ready`,
  unclaimed, routed to `model:sol` / `effort:high`, and assigned `Producer`
  acceptance.
- Canonical dependency: #40, closed and `Done` at claim time.
- Dependency justification: #40 freezes the provider-independent execution,
  evidence, geometry, confirmation, and stale-remap boundary that this engine
  decision must satisfy. Its accepted commit is `bd4b27d`.
- Product specification Revision 2.2 supplies the local-agent, immutable
  capture-revision, versioned adapter, no-silent-cookie, and visible-failure
  principles for Phase 5 webpage capture.

## Candidate set and fixed profiles

Evaluate only these already available local candidates on the same inputs:

1. Apple Vision `VNRecognizeTextRequest`, request revision 3, `.accurate`,
   explicit `en-US`, automatic language detection off, language correction off,
   and no custom words. The engine release is pinned by the evaluated macOS
   product version/build and adapter executable digest.
2. Tesseract 5.5.3, LSTM engine mode 1, automatic page segmentation mode 3,
   installed `eng.traineddata`, no preprocessing, and TSV output. The model is
   pinned by its exact file digest.

No candidate profile is tuned after seeing per-fixture results. A profile
change requires a new named evaluation run.

## Scope

1. Generate and retain a synthetic 1600×900 webpage-style raster corpus and
   machine-readable ground truth covering clean text, mixed columns/cards,
   small/scaled text, rotated text, multilingual behavior, and intentionally
   unreadable text.
2. Run both candidates repeatedly on byte-identical rasters and retain their
   canonical word/line text and source-pixel boxes.
3. Measure exact-text recall, matched-box intersection-over-union, identical-
   output repeatability, wall latency, peak resident memory, installed/supported
   languages, and confidence/geometry availability.
4. Record exact platform, engine, model/profile, package/source, license,
   privacy, offline behavior, update policy, executable/model/fixture/output
   digests, and known failures.
5. Recommend one pinned default and specify the exact #40-compatible execution
   profile, adapter mapping, preflight failures, and provenance fields #41 must
   record.

## Exclusions

- No live, production, private, authenticated, paywalled, or third-party page;
  no source URL, cookie, credential, user text, or research-project data.
- No browser, UI, DOM extraction, production capture, provider account, paid or
  external OCR, network OCR request, upload, Resolve/Fusion work, or database
  mutation.
- No implementation, promotion, claim, dispatch, or closure of #41.
- No shared-schema, generated-type, compiler, application, package-lock, or
  dependency change.
- No automatic confirmation: every OCR result remains proposal evidence under
  #40, regardless of measured confidence or benchmark score.

## Contracts, fixtures, and dependency changes

- Touched shared contracts: none.
- Touched `/fixtures`, accepted fixtures, tests, or goldens: none. The new
  synthetic benchmark corpus lives only beneath the issue #105 investigation
  directory, with its own generation metadata and hashes.
- New product/runtime dependencies: none. Evidence generation may use the
  existing bundled Pillow runtime, while both measured OCR engines are already
  installed local capabilities.
- Planned artifacts: this plan, one benchmark driver, one Vision probe, the
  synthetic corpus/ground truth, retained machine-readable results, and one
  producer-facing comparison/failure/handoff report.

## Selection rule

Choose the candidate that first satisfies all hard gates:

1. consumes only the authorized local raster/crop and performs no network
   transmission;
2. exposes word and line text with source-pixel geometry that can be converted
   into #40's integer half-open rectangles without invented values;
3. repeats byte-identically on identical input under the pinned profile;
4. has a lawful, supportable local packaging path and an enforceable update
   rule; and
5. can fail closed on unavailable engine/model, profile or model mismatch,
   invalid geometry, and unsupported language.

Among candidates passing every gate, prefer higher word/line geometry accuracy
and text recall; use latency/resource cost and language breadth as secondary
tradeoffs. If reproducibility and quality materially conflict, retain the
tradeoff for Producer judgment rather than silently changing the rule.

## Verification

1. Run the benchmark from a clean output directory twice and verify retained
   fixture and canonical OCR hashes are stable.
2. Verify both engines see the identical fixture digests and each candidate is
   repeated at least five times per fixture.
3. Verify the results include word/line accuracy, repeatability, latency,
   memory, language, platform, profile, model/package/license, and privacy
   evidence.
4. Exercise and retain model-digest-mismatch and unavailable-engine preflight
   failures; inspect unreadable, rotated/scaled, mixed-layout, confidence, and
   geometry behavior.
5. Run a sensitive-string and URL scan over all new artifacts; only fictional,
   synthetic content may appear.
6. Run `git diff --check`, inspect the complete scope diff, and run the
   repository's pinned `npm run validate` gate.
7. Commit and push only #105 artifacts, move #105 to `In review` with concrete
   evidence, and leave it there for Producer acceptance.

## Producer acceptance outline

The handoff will identify one exact comparison report and direct the Producer
to the candidate score table, representative boxes, repeatability/resource
evidence, privacy/license/platform/update decision, failure matrix, and #41
adapter/provenance section. The Producer records either
`Accepted Spotlight OCR engine selection.` or the first unacceptable accuracy,
privacy, licensing, or packaging tradeoff. Issue #105 remains `In review` until
that response is explicit.
