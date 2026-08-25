# Resolve Capability Matrix

This file records observed, version-stamped Resolve and interchange behavior.
Claims belong here only after they are exercised against the named real
installation and retained evidence. Code paths, mocks, documentation, and
expectations are not capability evidence.

## Current status

Slice 0.3 automation prepares and locally verifies dual trial inputs but does
not test Resolve behavior. No Resolve Free, Resolve Studio, OTIO-import, or
FCPXML-import capability is claimed yet. Noninteractive local inspection on
2026-08-24 detected macOS 15.1 build 24B83 (x86_64) and the standard
Blackmagic application at `/Applications/DaVinci Resolve/DaVinci Resolve.app`
reporting 21.0.4 / build 21.0.40005, with the `ManifestLite` package receipt
and no application `_MASReceipt`. These facts are detected-not-yet-tested and
do not establish edition or import capability.

## Resolve Free import observations

| Resolve version / installation | OS | Format | Item counts and durations | Track names/order | Media links | Markers | Transitions | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Detected, not yet tested: standard Blackmagic Resolve 21.0.4 (21.0.40005), ManifestLite, no MAS receipt | macOS 15.1 (24B83), x86_64 | OTIO | Not tested | Not tested | Not tested | Not tested | Not tested | `docs/slice-0.3-resolve-free-trial.md` pending worksheet | Unverified |
| Detected, not yet tested: standard Blackmagic Resolve 21.0.4 (21.0.40005), ManifestLite, no MAS receipt | macOS 15.1 (24B83), x86_64 | FCPXML | Not tested | Not tested | Not tested | Not tested | Not tested | `docs/slice-0.3-resolve-free-trial.md` pending worksheet | Unverified |

## Resolve Studio automation observations

| Resolve version / installation | OS | Edition detection | External scripting | Create/reopen/verify result | Safety-boundary result | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Pending Slice 0.4 | Pending | Not tested | Not tested | Not tested | Not tested | — | Unverified |

## Minimum supported versions

- Resolve Free: **Unresolved; requires Slice 0.3 evidence.**
- Resolve Studio: **Unresolved; requires Slice 0.4 evidence.**

## Observation template

For each run, retain the exact application edition/version, operating system,
installation source, input build/fixture hash, command or manual procedure,
expected result, observed result, discrepancies, evidence locator, date, and
observer.
