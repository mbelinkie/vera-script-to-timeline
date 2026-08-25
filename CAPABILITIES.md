# Resolve Capability Matrix

This file records observed, version-stamped Resolve and interchange behavior.
Claims belong here only after they are exercised against the named real
installation and retained evidence. Code paths, mocks, documentation, and
expectations are not capability evidence.

## Current status

Slice 0.3 automation prepares and locally verifies dual trial inputs, and
Slice 0.4 code/test doubles exercise the Studio adapter boundary. Neither has
tested real Resolve behavior. Noninteractive inspection on 2026-08-24 detected
macOS 15.1 build 24B83 (x86_64), the standard Blackmagic application at
`/Applications/DaVinci Resolve/DaVinci Resolve.app` reporting 21.0.4 / build
21.0.40005, the `ManifestLite` package receipt, no application `_MASReceipt`,
and installed scripting bridge/documentation. These are detected facts, not
evidence of edition, import fidelity, a Studio connection, or automation.

## Resolve Free import observations

| Resolve version / installation | OS | Format | Item counts and durations | Track names/order | Media links | Markers | Transitions | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Detected, not yet tested: standard Blackmagic Resolve 21.0.4 (21.0.40005), ManifestLite, no MAS receipt | macOS 15.1 (24B83), x86_64 | OTIO | Not tested | Not tested | Not tested | Not tested | Not tested | `docs/slice-0.3-resolve-free-trial.md` pending worksheet | Unverified |
| Detected, not yet tested: standard Blackmagic Resolve 21.0.4 (21.0.40005), ManifestLite, no MAS receipt | macOS 15.1 (24B83), x86_64 | FCPXML | Not tested | Not tested | Not tested | Not tested | Not tested | `docs/slice-0.3-resolve-free-trial.md` pending worksheet | Unverified |

## Resolve Studio automation observations

| Resolve version / installation | OS | Edition detection | External scripting | Create/reopen/verify result | Safety-boundary result | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Pending Slice 0.4 | Pending | Not tested | Not tested | Not tested | Not tested | — | Unverified |
| 21.0.4 / standard Blackmagic bundle, build 21.0.40005 | macOS 15.1 x86_64 | Not observed; bundle name is edition-neutral | Not attempted | Not attempted | Automated test doubles only; no real project mutation | Local `Info.plist`, receipt/module/docs presence; producer-run commands remain pending | Detected only / unverified |

## Minimum supported versions

- Resolve Free: **Unresolved; requires Slice 0.3 evidence.**
- Resolve Studio: **Unresolved; requires Slice 0.4 evidence.**

## Installed public API gaps relevant to Slice 0.4

The installed Resolve 21 documentation exposes
`InsertFusionTitleIntoTimeline(titleName)` and playhead positioning, but no
supported stock Fusion-title enumeration API and no supported destination
track selection API for title insertion. The spike can request `Text+` at the
frame-zero playhead and report whether insertion returned an item; it cannot
prove from the public API that the title was stock or force/prove V4 placement.
That remains an explicit manual-completion/capability observation, never a
private-API or UI-automation fallback.

Nonmutating preflight can inspect the project manager and, when one is open,
current Project/MediaPool settings and method surfaces. It cannot exercise
project creation, setting mutation, import, timeline assembly, or title
insertion. The CLI reports that gap instead of treating preflight as proof of
build success. The bounded spike also rejects nonzero timeline starts before
loading the vendor bridge.

## Observation template

For each run, retain the exact application edition/version, operating system,
installation source, input build/fixture hash, command or manual procedure,
expected result, observed result, discrepancies, evidence locator, date, and
observer.
