# OCR engine evaluation and pinning for Spotlight

## Outcome

Select one concrete OCR engine, model/profile, and local packaging approach
for VERA Spotlight.  The decision must be reproducible and compatible with the
already accepted evidence, provenance, confirmation, and stale-remap rules.

## Scope

- Compare a small, documented set of locally runnable OCR candidates using
  licensed or synthetic representative webpage screenshots.
- Measure word and line geometry accuracy, repeatability on identical input,
  latency/resource use, language coverage, and the ability to retain engine,
  model, profile, and output-evidence identities.
- Evaluate privacy, offline operation, license, platform packaging, and update
  behavior.  Do not send user pages or credentials to an external provider.
- Recommend and producer-approve one pinned engine/model/profile, with a
  reproducible fixture corpus and a clear adapter handoff for #41.

## Exclusions

- No production capture, browser/UI work, provider-account setup, paid or
  unsanctioned external OCR call, shared schema change, or #41 implementation.
- No live webpage content, private script text, or production artifact enters
  the evaluation corpus.

## Dependencies

- Blocked by #40

## Acceptance criteria

- [ ] Retained results compare at least two viable locally runnable candidates
  on the same non-sensitive fixture corpus, including word/line-box accuracy,
  repeatability, speed/resource use, and supported language behavior.
- [ ] The selected candidate identifies an exact engine release, model/profile,
  package/source, license, supported host platforms, update policy, and the
  provenance fields #41 must record.
- [ ] Privacy and packaging analysis demonstrates that the selected default can
  run locally without transmitting captured pages; every external alternative
  is explicitly rejected or separately authorized.
- [ ] A fixture and failure matrix covers unreadable text, rotated/scaled text,
  mixed layouts, confidence/geometry gaps, model mismatch, and unavailable
  engine behavior without silently confirming an OCR proposal.
- [ ] Producer reviews the comparison, accepts the pinned engine/profile and
  the adapter handoff, or records the first unacceptable tradeoff.

## Producer acceptance

1. Open the retained comparison and fixture/failure matrix.
2. Compare the chosen candidate's word/line boxes and repeatability against the
   same examples used for each alternative.
3. Confirm the selected default is local, licensed, and does not transmit page
   content, then review the exact pinned version/model/profile and update rule.
4. Confirm #41 receives a concrete adapter/provenance handoff rather than
   authority to choose a different engine.
5. Reply `Accepted Spotlight OCR engine selection.` or identify the first
   unacceptable accuracy, privacy, licensing, or packaging result.

## Rationale

This is a decision-and-evaluation slice.  It deliberately sits after #40's
provider-independent contract and before #41's adapter implementation so the
implementation cannot silently pick a provider or model.
