# Resolve Capability Matrix

This file records observed, version-stamped Resolve and interchange behavior.
Claims belong here only after they are exercised against the named real
installation and retained evidence. Code paths, mocks, documentation, and
expectations are not capability evidence.

## Current status

Slice 0.3 automation prepares and locally verifies dual trial inputs. Producer
testing in real Resolve Free 21 on an Intel Mac found that OTIO imported all
five expected linked items and retained the expected marker. FCPXML imported
the same five items only after the producer redirected Resolve to the packaged
media and did not retain the marker. No other difference was observed. The
producer accepted Slice 0.3 and approved D-P005 to park FCPXML. Slice 0.4
producer preflight connected through the supported external API to real
DaVinci Resolve Studio 21.0.4 build 5 with external scripting available. The
connected identity agreed with the detected local bundle and the preflight
reported no discrepancies or project mutation. On 2026-08-25 the supported
API then created project
`VERA Slice 0.4 Producer Acceptance 20260825-021704`, saved it, closed it,
reopened it, and verified every public-API-observable spike requirement with
no discrepancy. The producer visually inspected the result and explicitly
accepted Slice 0.4 on 2026-08-25, including the documented V1/120-frame Text+
limitation. The limitation remains open and is isolated in
`docs/resolve-text-plus-destination-track-limitation.md`.
Noninteractive inspection on 2026-08-24 detected macOS 15.1 build 24B83
(x86_64), the default-path application bundle at
`/Applications/DaVinci Resolve/DaVinci Resolve.app` reporting 21.0.4 / build
21.0.40005, a matching `ManifestLite` 21.0.4 package receipt, no application
`_MASReceipt`, and installed scripting bridge/documentation. These are
detected facts, not proof of the connected executable path and not evidence of
the exact in-application patch/build, complete import fidelity, a Studio
connection, or automation.

## Resolve Free import observations

| Resolve version / installation | OS | Format | Item counts and durations | Track names/order | Media links | Markers | Transitions | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Producer reported Resolve Free 21; default-path bundle separately detected as 21.0.4 (21.0.40005) | macOS 15.1 (24B83), x86_64 | OTIO | 4 picture + 1 audio; no timing discrepancy noticed | No discrepancy noticed | All 5 linked; no relink issue reported | Expected marker present | No discrepancy noticed | Producer worksheet at `docs/slice-0.3-resolve-free-trial.md`, 2026-08-24 | Accepted Slice 0.3 baseline |
| Producer reported Resolve Free 21 installed from Blackmagic download; default-path bundle separately detected as 21.0.4 (21.0.40005) | macOS 15.1 (24B83), x86_64 | FCPXML | 4 picture + 1 audio after media redirect; no timing discrepancy noticed | No discrepancy noticed | All 5 linked after manual redirect to packaged media | Expected marker missing | No discrepancy noticed | Producer worksheet at `docs/slice-0.3-resolve-free-trial.md`, 2026-08-24 | Producer-observed import completed with marker and initial-linking discrepancies |

## Resolve Studio automation observations

| Resolve version / installation | OS | Edition detection | External scripting | Create/reopen/verify result | Safety-boundary result | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 21.0.4 / default-path bundle with matching ManifestLite receipt, build 21.0.40005 | macOS 15.1 x86_64 | Real API connection reported `DaVinci Resolve Studio`, version 21.0.4, build 5, empty suffix | Available through the supported local external scripting API | Project `VERA Slice 0.4 Producer Acceptance 20260825-021704` was created, configured, populated, saved, closed, reopened, and verified with no public-API-observable discrepancies. The verified timeline is `VERA build 00000000-0000-4000-8000-000000000103`. | Initial bridge-loader attempt and two pre-restart connection attempts stopped safely before mutation. Every post-restart preflight passed without mutation. Failed uniquely named build attempts were retained rather than overwritten or deleted; the final uniquely named build verified. | Producer terminal JSON and Resolve project, 2026-08-25; loader fix `94bdd53`; still-range hardening in the current Slice 0.4 diff; orchestration records in `docs/IMPLEMENTATION_PROGRESS.md` and `docs/ORCHESTRATION_PROGRESS_2026-08-25.md`; focused limitation note in `docs/resolve-text-plus-destination-track-limitation.md` | Accepted Slice 0.4 baseline; V1/120-frame Text+ limitation retained as an open capability gap |

## Minimum supported versions

- Resolve Free: **Tested baseline is Resolve Free 21 on the detected 21.0.4 /
  build 21.0.40005 bundle. A true minimum is not claimed without lower-version
  evidence.**
- Resolve Studio: **Tested build baseline is Studio 21.0.4 / API build 5 on
  the detected 21.0.4 / bundle build 21.0.40005 installation. A true minimum
  is not claimed without lower-version evidence.**

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
loading the vendor bridge, requires a documented timeline page before mutation,
and cannot prove the connected executable path because the public API does not
report it.

Resolve 21.0.4 ignored `AppendToTimeline`'s ordinary requested end frame for a
one-frame PNG and initially inserted the user-preference default duration of
120 frames. `MediaPoolItem.SetClipProperty("Duration", ...)` returned false.
The documented media-pool mark range did control the still, but its interaction
with `clipInfo.endFrame` required an observed one-frame compensation: mark out
18 plus clip end 19 produced the required 18-frame occurrence, while mark out
18 plus clip end 18 produced 17 frames. The final build uses that checked
Resolve 21 behavior, clears the temporary mark immediately after append, and
verifies the reopened occurrence duration and media identity.

## Interchange decision

OTIO is the maintained interchange path for the tested Resolve Free workflow.
FCPXML is parked under accepted decision D-P005: it required a manual media
redirect, omitted the expected marker, and closed no observed OTIO gap. The
bounded deterministic FCPXML spike remains in the repository as contingency
evidence, not as a committed product output path.

## Observation template

For each run, retain the exact application edition/version, operating system,
installation source, input build/fixture hash, command or manual procedure,
expected result, observed result, discrepancies, evidence locator, date, and
observer.
