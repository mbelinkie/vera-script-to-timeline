# Slice 0.3 producer runbook and evidence worksheet

This is a manual trial against actual Resolve Free. The generated files are
locally verified inputs; they are not evidence of Resolve import fidelity.
Do not launch Resolve through an agent, automate its UI, or write observations
that the producer did not make.

## Prepare inputs

From a locked repository install, run the Slice 0.3 command in `README.md`.
Keep each interchange file beside its own `media/` directory. In Resolve Free,
create two fresh empty projects/timelines under the same project settings. Use
**File > Import > Timeline** to import OTIO first and FCPXML second. Do not fix
or relink either result until the initial state and evidence are recorded.

## Environment (record before import)

- Date/time and observer:
- OS product/version/build and architecture:
- Resolve edition:
- Resolve version/build shown inside the application:
- Install source (Blackmagic download, App Store, other):
- Package/receipt evidence locator:
- Trial package path or retained archive:
- Manifest SHA-256:
- OTIO SHA-256:
- FCPXML SHA-256:

Repository-side detection on 2026-08-24 found, but has **not tested**:

- macOS 15.1 build 24B83, x86_64;
- default-path `/Applications/DaVinci Resolve/DaVinci Resolve.app` reporting
  version 21.0.4 and build 21.0.40005;
- matching installed package receipt `com.blackmagic-design.ManifestLite`
  version 21.0.4; and
- no `_MASReceipt` in the application bundle.

Confirm the edition/version/build in Resolve itself before treating these as
the trial environment. Detection is not a capability observation.

## Expected manifest facts

- Timeline: 72 frames at 24000/1001 fps, 1920×1080, 48 kHz.
- Events: 4 picture events on `V3 B-roll / stills` (18 frames each, starting
  at 0/18/36/54) and 1 audio event on `A1 Narration 1` (72 frames at 0).
- Picture source starts: 2, 4, 6, then 0 frames for the still.
- Tracks, in manifest order: V1, V2, V3, V4, V5, A1, A2, A3, A4, A5, S1,
  with their full names in `timeline-manifest.json`.
- One blue `Producer review` marker at frame 33.
- Three zero-duration hard cuts at frames 18, 36, and 54; no transition effect.

## OTIO observation

- Import outcome/error text:
- Timeline item count and per-item duration/start/source-in:
- Timeline total duration/rate/resolution/audio rate:
- Track names and top-to-bottom order (include missing/extra tracks):
- Media link status for each of five sources:
- Marker name/frame/note/color:
- Cuts/transitions at frames 18/36/54:
- Discrepancies from the expected manifest facts:
- Evidence locators (screenshots, exported timeline, notes/logs):

## FCPXML observation

- Import outcome/error text:
- Timeline item count and per-item duration/start/source-in:
- Timeline total duration/rate/resolution/audio rate:
- Track names and top-to-bottom order (include missing/extra tracks):
- Media link status for each of five sources:
- Marker name/frame/note/color:
- Cuts/transitions at frames 18/36/54:
- Discrepancies from the expected manifest facts:
- Evidence locators (screenshots, exported timeline, notes/logs):

## Comparison and exit decision

- Gaps common to both:
- OTIO-only gaps:
- FCPXML-only gaps:
- Does FCPXML close a material OTIO gap? State exact evidence:
- Proposed D-P005 outcome: **maintain FCPXML fallback / park FCPXML**
- Rationale and compatibility/acceptance impact:

After both observations are complete, transfer only objective results and
evidence locators into `CAPABILITIES.md`; resolve D-P001, D-P002, and D-P005 in
`DECISIONS.md`. The producer—not the generated package or agent report—accepts
the slice.
