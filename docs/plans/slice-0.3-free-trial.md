# Slice 0.3 — Resolve Free dual-input trial preparation

## Bounded scope

Prepare the producer-run Resolve Free comparison without claiming its result:

1. deterministically materialize and structurally/semantically verify an FCPXML
   evidence spike from the exact accepted Slice 0.2 manifest and media;
2. expose one command that creates separate self-contained, verified OTIO and
   FCPXML trial inputs; and
3. provide an evidence worksheet for the producer's manual imports into the
   actual Resolve Free installation.

The FCPXML writer is a trial artifact. Its presence does not decide that
FCPXML will be a maintained product fallback.

## Explicit exclusions

- Launching, scripting, or automating Resolve, and manipulating its UI.
- Resolve Studio, the product Free adapter, compiler, jobs, persistence, or UI.
- Any inferred import observation, capability claim, minimum-version claim, or
  FCPXML fallback decision before the producer performs both manual imports.
- Changes to `/contracts`, `/fixtures`, generated contract outputs, or accepted
  Slice 0.2 tests.

## Contracts, fixtures, and dependencies

This slice consumes the accepted `TimelineManifest v1` and the exact Slice 0.2
handcrafted manifest/media read-only. No frozen asset is changed. No dependency
is added: Python's standard XML library is sufficient for this bounded spike,
and the OTIO side reuses the exact-pinned accepted Slice 0.2 implementation.

## Automated checks

- Parse FCPXML and compare timeline settings, manifest/track metadata, every
  source, event record/source range, marker, and hard cut to the manifest.
- Verify self-contained media inventory, regular-file boundaries, and hashes.
- Prove byte-identical repeated output and exercise alternate delivery settings
  and track IDs/names/order.
- Exercise the documented dual-input CLI and reject tampered XML/media.
- Run locked installs, focused tests, the full validation command, and a frozen
  boundary diff audit.

## Producer acceptance checklist

1. Generate the dual trial package using the README command.
2. Complete `docs/slice-0.3-resolve-free-trial.md` while manually importing the
   OTIO and FCPXML inputs into the named Resolve Free installation.
3. Record exact environment, counts/durations, tracks, links, marker,
   transitions, discrepancies, and retained evidence for both formats.
4. Compare results and update `CAPABILITIES.md` only with observed facts.
5. Resolve D-P005 in `DECISIONS.md`, with evidence, by enabling FCPXML as a
   maintained fallback or parking it.

Automated preparation does not accept the slice; producer observation is the
authoritative acceptance gate.
